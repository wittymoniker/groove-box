"""program_builder.py — compile and run full programs in any installed language, on the sCode 'programs' direction.

Languages (used when the toolchain is installed; the window says which are):
  C (gcc / clang) · C++ (g++ / clang++) · Rust (rustc) · Go (go build) · Julia (pre-provisioned julia) ·
  Lua (luajit / lua, or the bundled LuaJIT through lupa) · Python (python3; optional PyInstaller / Nuitka for a
  standalone binary) · Shell (sh)
Every program gets the Groovebox environment (GROOVEBOX_SEED, _BPM, _BASE_HZ, _PROJECT, _OUT …) and its output folder;
files it writes there come back into Groovebox by type (WAV → carrier, OBJ → video OBJ, PNG → background …).
Build products go to <exports>/programs/<name>/. Compiles and runs never block the window.
"""
from __future__ import annotations
import json, os, shutil, subprocess, sys, time

LANGS = {
    ".c": ("C", lambda src, out: [_cc(), "-O2", "-o", out, src, "-lm"]),
    ".cpp": ("C++", lambda src, out: [_cxx(), "-O2", "-std=c++17", "-o", out, src]),
    ".rs": ("Rust", lambda src, out: ["rustc", "-O", "-o", out, src]),
    ".go": ("Go", lambda src, out: ["go", "build", "-o", out, src]),
    ".jl": ("Julia", None), ".lua": ("Lua", None), ".py": ("Python", None), ".sh": ("Shell", None),
}


def _cc():
    return __import__("sos_tools").which("gcc") or __import__("sos_tools").which("clang") or __import__("sos_tools").which("cc") or "cc"


def _cxx():
    return __import__("sos_tools").which("g++") or __import__("sos_tools").which("clang++") or "c++"


def toolchains():
    """Report installed runtimes only; the appliance provisions these at image build/first launch."""
    import importlib.util
    which = __import__("sos_tools").which
    try:
        lupa_ready = importlib.util.find_spec("lupa.luajit21") is not None or importlib.util.find_spec("lupa") is not None
    except Exception:
        lupa_ready = False
    try:
        juliacall_ready = importlib.util.find_spec("juliacall") is not None
    except Exception:
        juliacall_ready = False
    return {
        "C": bool(which("gcc") or which("clang") or which("cc")),
        "C++": bool(which("g++") or which("clang++") or which("c++")),
        "Rust": bool(which("rustc")),
        "Go": bool(which("go")),
        "Julia": bool(which("julia")),
        "JuliaCall": bool(juliacall_ready),
        "Lua": bool(which("luajit") or which("lua") or lupa_ready),
        "Python": bool(sys.executable),
        "Shell": bool(which("sh")),
        "PyInstaller": bool(which("pyinstaller")),
        "LuaJIT": bool(which("luajit") or lupa_ready),
    }


def out_dir(app, name):
    d = os.path.join(str(app._exports_dir()), "programs", os.path.splitext(os.path.basename(name))[0]); os.makedirs(d, exist_ok=True)
    return d


def env_for(app, outd):
    try:
        import app_hub
        env = app_hub.script_env(app, outd)
    except Exception:
        env = dict(os.environ); env["GROOVEBOX_OUT"] = outd
    env["GROOVEBOX_HOME"] = os.path.dirname(os.path.abspath(__file__))
    env["PYTHONPATH"] = os.pathsep.join([os.path.join(env["GROOVEBOX_HOME"], "plugin_sandbox"),   # R101: system-file audit hook
                                         env["GROOVEBOX_HOME"], os.path.join(env["GROOVEBOX_HOME"], "plugins_library"), env.get("PYTHONPATH", "")])
    env["GROOVEBOX_PLUGIN_SANDBOX"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if os.environ.get("GROOVEBOX_PLUGIN_SEED"):
        env["GROOVEBOX_SEED"] = os.environ["GROOVEBOX_PLUGIN_SEED"]     # a plugin's own random app state
    env["GROOVEBOX_REQUESTS"] = os.path.join(outd, "groovebox_requests.json")
    try:
        import plugin_guard
        env = plugin_guard.clean_env(env)
    except Exception:
        pass
    return env


def build(app, src, standalone=False):
    """Compile src. Returns (ok, argv to run, log)."""
    ext = os.path.splitext(src)[1].lower(); lang, cmd = LANGS.get(ext, ("?", None)); d = out_dir(app, src)
    exe = os.path.join(d, os.path.splitext(os.path.basename(src))[0] + (".exe" if os.name == "nt" else ""))
    if cmd is not None:
        r = subprocess.run(cmd(src, exe), capture_output=True, text=True, timeout=600, cwd=os.path.dirname(src) or None)
        return r.returncode == 0, [exe], (r.stdout + r.stderr)[-4000:] or "compiled %s → %s" % (lang, exe)
    if ext == ".py":
        if standalone and __import__("sos_tools").which("pyinstaller"):
            r = subprocess.run(["pyinstaller", "--onefile", "--distpath", d, "--workpath", os.path.join(d, "build"), src], capture_output=True, text=True, timeout=1800)
            return r.returncode == 0, [os.path.join(d, os.path.splitext(os.path.basename(src))[0])], (r.stdout + r.stderr)[-4000:]
        check = subprocess.run(
            [sys.executable, "-B", "-c", "from pathlib import Path; import sys; p=Path(sys.argv[1]); compile(p.read_bytes(), str(p), 'exec')", src],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        return check.returncode == 0, [sys.executable, "-B", src], (check.stdout + check.stderr)[-4000:] or "syntax checked in memory; runs with the bundled Python"
    if ext == ".lua":
        lj = __import__("sos_tools").which("luajit") or __import__("sos_tools").which("lua")
        if lj:
            if standalone and __import__("sos_tools").which("luajit"):
                bc = os.path.join(d, os.path.basename(src) + "c")
                r = subprocess.run(["luajit", "-b", src, bc], capture_output=True, text=True); return r.returncode == 0, [lj, bc], r.stderr or "bytecode " + bc
            return True, [lj, src], "runs with " + lj
        return True, [sys.executable, "-c", "import lupa.luajit21 as l,sys;r=l.LuaRuntime();r.execute(open(sys.argv[1]).read())", src], "runs with the built-in LuaJIT (lupa)"
    if ext == ".jl":
        julia = __import__("sos_tools").which("julia")
        if julia:
            return True, [julia, "--startup-file=no", "-O2", src], "runs with the pre-provisioned Julia runtime"
        return False, [], "Julia runtime is unavailable. This appliance should provide Julia automatically; check Performance → Info / runtime diagnostics and repair the ISO runtime rather than downloading a private Julia copy."
    if ext == ".sh":
        return True, ["sh", src], "shell script"
    return False, [], "unknown language for %s" % src


def run(app, argv, outd, on_line=None):
    """Run a built program; returns (returncode, new files). Output files are sent back into Groovebox."""
    before = set(os.listdir(outd)) if os.path.isdir(outd) else set()
    import app_limits   # user programs stay strictly under the external share of CPU / memory
    p = app_limits.popen(argv, env=env_for(app, outd), cwd=outd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    t0 = time.monotonic()
    for line in p.stdout:
        if on_line: on_line(line.rstrip())
        if time.monotonic() - t0 > float(os.environ.get("GROOVEBOX_PROGRAM_TIMEOUT", "1800")):
            p.kill(); on_line and on_line("stopped: wall-time limit"); break
    rc = p.wait()
    new = [os.path.join(outd, f) for f in sorted(set(os.listdir(outd)) - before)]
    return rc, new



def open_window(app, path=None):
    from PyQt6.QtCore import Qt, QObject, pyqtSignal
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QPlainTextEdit, QLabel, QFileDialog, QCheckBox)

    class Br(QObject):
        line = pyqtSignal(str)
    d = QDialog(app); d.setWindowTitle("🛠 Program Builder · compile and run full programs"); d.resize(900, 600); d.setWindowModality(Qt.WindowModality.NonModal)
    lay = QVBoxLayout(d)
    runtime_label = QLabel("")
    runtime_label.setWordWrap(True)
    lay.addWidget(runtime_label)
    def refresh_toolchain_status():
        current = toolchains()
        core = ("C", "C++", "Rust", "Go", "Julia", "Lua", "Python", "Shell")
        runtime_label.setText("Prepared runtimes: " + " · ".join(("✓ " if current.get(k) else "✗ ") + k for k in core)
                              + "\nBridges / optional packaging: " + ("✓ JuliaCall" if current.get("JuliaCall") else "✗ JuliaCall")
                              + " · " + ("✓ PyInstaller" if current.get("PyInstaller") else "— PyInstaller")
                              + " · " + ("✓ LuaJIT" if current.get("LuaJIT") else "— LuaJIT"))
        return current
    refresh_toolchain_status()
    row = QHBoxLayout(); lay.addLayout(row)
    b_open = QPushButton("Open source…"); standalone = QCheckBox("standalone build (PyInstaller / luajit -b)")
    b_build = QPushButton("⚙ Build"); b_run = QPushButton("▶ Run"); b_refresh = QPushButton("↻ Refresh runtimes")
    for w in (b_open, standalone, b_build, b_run, b_refresh): row.addWidget(w)
    b_refresh.clicked.connect(refresh_toolchain_status)
    src_lab = QLabel(path or "no source"); lay.addWidget(src_lab)
    log = QPlainTextEdit(); log.setReadOnly(True); log.setFont(QFont("Monospace", 9)); lay.addWidget(log, 1)
    br = Br(d); br.line.connect(log.appendPlainText)
    st = {"src": path, "argv": None}

    def bg(fn):
        try:
            import scode_coordinator as sc
            return sc.direct("programs", fn)
        except Exception:
            import threading; threading.Thread(target=fn, daemon=True).start()

    def do_build():
        if not st["src"]: return
        def job():
            ok, argv, txt = build(app, st["src"], standalone.isChecked()); st["argv"] = argv if ok else None
            br.line.emit(("✓ " if ok else "✖ ") + txt)
        bg(job)

    def do_run():
        if not st["src"]: return
        def job():
            if st["argv"] is None:
                ok, argv, txt = build(app, st["src"], False); br.line.emit(txt)
                if not ok: return
                st["argv"] = argv
            outd = out_dir(app, st["src"]); t0 = time.time()
            rc, new = run(app, st["argv"], outd, br.line.emit)
            br.line.emit("exit %d · %.1f s · %d new file(s)" % (rc, time.time() - t0, len(new)))
            st["new"] = new
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: (apply_req(outd), send_back(new, outd)))
        bg(job)

    def apply_req(outd):
        req = os.path.join(outd, "groovebox_requests.json")
        if os.path.isfile(req):
            try:
                import plugin_guard
                ops = __import__("safe_io").load_json(req)
                n, bad = plugin_guard.apply_requests(app, ops if isinstance(ops, list) else [], who=os.path.basename(st["src"]), root=outd)
                log.appendPlainText("requests: %d applied, %d refused" % (n, len(bad)))
            except Exception as exc:
                log.appendPlainText("requests: %s" % exc)
            try: os.remove(req)
            except OSError: pass

    def send_back(files, outd=None):
        try:
            import app_hub, plugin_guard
            files = plugin_guard.guard_outputs(app, outd or os.path.dirname(files[0]) if files else "", files, os.path.basename(st["src"] or "program"))
            for f in files or []:
                log.appendPlainText("→ " + str(app_hub.send_back(app, f)))
                try: __import__("experiences").record(app, f, "program", {"program": st["src"]})
                except Exception: pass
        except Exception as exc:
            log.appendPlainText("send back: %s" % exc)

    def opn():
        p, _ = QFileDialog.getOpenFileName(d, "Program source", os.path.expanduser("~"), "Sources (*.c *.cpp *.rs *.go *.jl *.lua *.py *.sh)")
        if p: st["src"] = p; st["argv"] = None; src_lab.setText(p)
    b_open.clicked.connect(opn); b_build.clicked.connect(do_build); b_run.clicked.connect(do_run)
    d.show(); app._program_builder = d
    d._run_now = do_run
    return d
