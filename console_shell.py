"""console_shell.py (R132): shell commands, shell scripts, sudo and full Python for the Command Console.

Console syntax (see command_console.py):
    !<command>            run a shell command (bash -lc), output streams into the console, ⏹ Stop kills it
    sudo <command>        the same as root; asks for the password once (sudo keeps it for 10 minutes)
    run <file> [args]     run a script: .sh / no extension -> bash, .py -> this console's Python
    py <code>  / >>> code full Python (real builtins, persistent variables; app, sh(), sudo(), run())
    passwd                change the appliance user's password (used by sudo)

Python helpers available after ``py``:
    sh("ls -l")                  -> output text (never raises; exit code: last_rc())
    sudo("apt-get update")       -> output text, as root
    run("~/build.sh", "arg")     -> output text

Default password on the sOS ISO: "groovebox" (set at build time only when the account had none). Change it with
``passwd``. Nothing here is reachable from the network: it runs only from the console window on the machine.
"""
from __future__ import annotations

import contextlib
import io
import os
import shlex
import shutil
import signal
import subprocess
import threading
import traceback
from pathlib import Path

DEFAULT_PASSWORD_HINT = 'sOS default password: "groovebox" (change it with: passwd)'
_NS: dict = {}
_LAST = {"rc": None}


def _bash():
    return shutil.which("bash") or "/bin/sh"


def _env():
    env = dict(os.environ)
    env.setdefault("TERM", "dumb")
    env["SUDO_ASKPASS"] = env.get("SUDO_ASKPASS", "")
    for extra in ("/usr/sbin", "/sbin", "/usr/local/sbin", "/opt/sos/bin"):
        if extra not in env.get("PATH", "").split(":"):
            env["PATH"] = env.get("PATH", "/usr/bin:/bin") + ":" + extra
    return env


def sudo_mode():
    """'root' | 'cached' (no password needed now) | 'password' | 'pkexec' | None."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return "root"
    if shutil.which("sudo"):
        try:
            r = subprocess.run(["sudo", "-n", "true"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=8)
            if r.returncode == 0:
                return "cached"
        except Exception:
            pass
        return "password"
    if shutil.which("pkexec"):
        return "pkexec"
    return None


def shell_argv(cmd, privileged=False, password=None):
    """(argv, stdin_text or None) for one shell command line."""
    base = [_bash(), "-lc", cmd] if _bash().endswith("bash") else [_bash(), "-c", cmd]
    if not privileged:
        return base, None
    mode = sudo_mode()
    if mode == "root":
        return base, None
    if mode == "cached":
        return ["sudo", "-n", "--"] + base, None
    if mode == "password":
        if password is None:
            raise PermissionError("sudo needs the password")
        return ["sudo", "-S", "-p", "", "--"] + base, password + "\n"
    if mode == "pkexec":
        return ["pkexec"] + base, None
    raise PermissionError("no sudo or pkexec on this system")


def script_argv(path, args=()):
    p = os.path.expanduser(str(path))
    if not os.path.isfile(p):
        raise FileNotFoundError(p)
    return [_bash(), p, *map(str, args)]


class Job:
    """One running process; lines go to on_line (any thread), on_done(rc) at the end."""

    def __init__(self, argv, stdin_text=None, on_line=None, on_done=None, cwd=None, timeout=None):
        self.argv, self.stdin_text = argv, stdin_text
        self.on_line, self.on_done = on_line, on_done
        self.cwd = cwd or str(Path.home())
        self.timeout = timeout
        self.proc = None
        self.output = []
        self.rc = None
        self._t = None

    def start(self, wait=False):
        self.proc = subprocess.Popen(self.argv, stdin=subprocess.PIPE if self.stdin_text is not None else subprocess.DEVNULL,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
                                     errors="replace", cwd=self.cwd, env=_env(), start_new_session=True)
        if self.stdin_text is not None:
            try:
                self.proc.stdin.write(self.stdin_text); self.proc.stdin.close()
            except Exception:
                pass
        self._t = threading.Thread(target=self._pump, name="console-shell", daemon=True)
        self._t.start()
        if self.timeout:
            threading.Timer(self.timeout, self.stop).start()
        if wait:
            self._t.join()
        return self

    def _pump(self):
        try:
            for line in self.proc.stdout:
                self.output.append(line)
                if self.on_line:
                    try:
                        self.on_line(line.rstrip("\n"))
                    except Exception:
                        pass
        finally:
            self.rc = self.proc.wait()
            _LAST["rc"] = self.rc
            if self.on_done:
                try:
                    self.on_done(self.rc)
                except Exception:
                    pass

    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def stop(self):
        """Stop the whole process group (the command and anything it started)."""
        if not self.running():
            return
        try:
            os.killpg(self.proc.pid, signal.SIGTERM)
        except Exception:
            try:
                self.proc.terminate()
            except Exception:
                pass
        def _kill():
            if self.running():
                try:
                    os.killpg(self.proc.pid, signal.SIGKILL)
                except Exception:
                    pass
        threading.Timer(3.0, _kill).start()

    def text(self):
        return "".join(self.output)


def _sync(argv, stdin_text=None, timeout=600):
    j = Job(argv, stdin_text, timeout=timeout).start(wait=True)
    out = j.text()
    return out + ("" if j.rc == 0 else f"[exit {j.rc}]\n")


# ------------------------------------------------------------------ Python helpers
def sh(cmd, timeout=600):
    return _sync(shell_argv(cmd)[0], timeout=timeout)


def sudo(cmd, password=None, timeout=3600):
    if password is None and sudo_mode() == "password":
        ask = _NS.get("_ask_password")
        password = ask() if callable(ask) else None
        if password is None:
            return "sudo cancelled\n"
    argv, stdin = shell_argv(cmd, privileged=True, password=password)
    return _sync(argv, stdin, timeout=timeout)


def run(path, *args, timeout=3600):
    p = os.path.expanduser(str(path))
    if p.endswith(".py"):
        return run_python(Path(p).read_text(encoding="utf-8", errors="replace"), filename=p)
    return _sync(script_argv(p, args), timeout=timeout)


def last_rc():
    """Exit code of the last shell command / script."""
    return _LAST["rc"]


def namespace(app=None):
    if not _NS:
        import sys
        _NS.update({"__name__": "__console__", "__builtins__": __builtins__, "os": os, "sys": sys,
                    "subprocess": subprocess, "Path": Path, "shlex": shlex,
                    "sh": sh, "sudo": sudo, "run": run, "last_rc": last_rc})
        for name, mod in (("np", "numpy"), ("mm", "memory_manager"), ("rg", "resource_governor")):
            try:
                _NS[name] = __import__(mod)
            except Exception:
                pass
    if app is not None:
        _NS["app"] = app
    return _NS


def run_python(src, app=None, filename="<console>"):
    """Run Python like an interactive prompt: an expression prints its value, statements just run."""
    ns = namespace(app)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            try:
                code = compile(src, filename, "eval")
            except SyntaxError:
                code = None
            if code is not None:
                value = eval(code, ns)
                if value is not None:
                    ns["_"] = value
                    print(repr(value))
            else:
                exec(compile(src, filename, "exec"), ns)
        except SystemExit as exc:
            print(f"(exit {exc.code} ignored: the console stays open)")
        except BaseException:
            traceback.print_exc()
    return buf.getvalue() or "(ok)"


def passwd_job(new_password, old_password=None, on_line=None, on_done=None):
    """Change the appliance user's password through sudo + chpasswd (old password = sudo password)."""
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or "groovebox"
    try:
        import pwd
        user = pwd.getpwuid(os.getuid()).pw_name
    except Exception:
        pass
    mode = sudo_mode()
    chp = shutil.which("chpasswd") or "/usr/sbin/chpasswd"
    line = f"{user}:{new_password}\n"
    if mode == "root":
        return Job([chp], line, on_line, on_done)
    if mode == "cached":
        return Job(["sudo", "-n", chp], line, on_line, on_done)
    if mode == "password":
        if old_password is None:
            raise PermissionError("current password needed")
        return Job(["sudo", "-S", "-p", "", chp], old_password + "\n" + line, on_line, on_done)
    raise PermissionError("no sudo on this system")
