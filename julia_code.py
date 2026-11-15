"""Shared JuliaCode runtime for the DSP bridge and developer tools.

Julia remains optional: no runtime is downloaded, no package is installed, and
no Julia code runs until a developer explicitly asks to check or run a file.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional, Sequence

ROOT = Path(__file__).resolve().parent
PROJECT_DIR = ROOT / "julia"
MAX_SOURCE_BYTES = 1_000_000
MAX_OUTPUT_CHARS = 250_000
DEFAULT_TIMEOUT = 120


@dataclass(frozen=True)
class JuliaResult:
    ok: bool
    action: str
    executable: str = ""
    version: str = ""
    returncode: int = -1
    stdout: str = ""
    stderr: str = ""
    elapsed_seconds: float = 0.0
    timed_out: bool = False
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def julia_executable() -> Optional[str]:
    """Return the configured Julia CLI if present; never install or download it."""
    configured = (os.environ.get("GROOVEBOX_JULIA_EXECUTABLE") or
                  os.environ.get("JULIA") or "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return str(candidate.resolve())
        found = shutil.which(configured)
        if found:
            return found
        return None
    return shutil.which("julia")


def julia_project_dir() -> Path:
    return PROJECT_DIR


def workspace_dir() -> Path:
    configured = os.environ.get("GROOVEBOX_JULIA_WORKSPACE", "").strip()
    if configured:
        root = Path(configured).expanduser()
    else:
        data = os.environ.get("XDG_DATA_HOME", "").strip()
        base = Path(data).expanduser() if data else Path.home() / ".local" / "share"
        root = base / "matgroovebox" / "julia-workspace"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def command_for_file(path: str | os.PathLike[str], extra: Sequence[str] = ()) -> list[str]:
    exe = julia_executable()
    if not exe:
        raise FileNotFoundError("Julia is not installed. Install Julia or set GROOVEBOX_JULIA_EXECUTABLE.")
    file_path = Path(path).expanduser().resolve()
    return [exe, "--startup-file=no", "--history-file=no",
            f"--project={PROJECT_DIR}", str(file_path), *map(str, extra)]


def runtime_status(timeout: float = 8.0) -> dict:
    exe = julia_executable()
    if not exe:
        return {"available": False, "executable": "", "version": "",
                "project": str(PROJECT_DIR), "message": "Julia CLI not found; saved code remains available."}
    try:
        result = subprocess.run([exe, "--version"], capture_output=True, text=True,
                                timeout=max(1.0, min(float(timeout), 20.0)), check=False)
        version = (result.stdout or result.stderr).strip()[:300]
        return {"available": result.returncode == 0, "executable": exe,
                "version": version, "project": str(PROJECT_DIR),
                "message": version if result.returncode == 0 else (result.stderr or "Julia version check failed")[-1000:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "executable": exe, "version": "",
                "project": str(PROJECT_DIR), "message": f"{type(exc).__name__}: {exc}"}


def _temporary_source(source: str, filename: str = "untitled.jl") -> tuple[Path, Path]:
    text = str(source)
    if len(text.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise ValueError(f"Julia source exceeds the {MAX_SOURCE_BYTES:,}-byte editor limit")
    root = workspace_dir()
    safe_name = Path(filename).name
    if not safe_name.lower().endswith(".jl"):
        safe_name += ".jl"
    fd, raw = tempfile.mkstemp(prefix=".groovebox-julia-", suffix=".jl", dir=str(root))
    path = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        return path, root
    except Exception:
        path.unlink(missing_ok=True)
        raise


def _run_command(command: list[str], *, action: str, cwd: Path,
                 timeout: float = DEFAULT_TIMEOUT) -> JuliaResult:
    exe = command[0]
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            command, cwd=str(cwd), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=max(1.0, min(float(timeout), 600.0)),
            check=False,
        )
        return JuliaResult(
            ok=proc.returncode == 0, action=action, executable=exe,
            returncode=int(proc.returncode), stdout=(proc.stdout or "")[-MAX_OUTPUT_CHARS:],
            stderr=(proc.stderr or "")[-MAX_OUTPUT_CHARS:],
            elapsed_seconds=time.perf_counter() - started,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes): stdout = stdout.decode("utf-8", "replace")
        if isinstance(stderr, bytes): stderr = stderr.decode("utf-8", "replace")
        return JuliaResult(False, action, exe, returncode=-1,
                           stdout=str(stdout)[-MAX_OUTPUT_CHARS:],
                           stderr=str(stderr)[-MAX_OUTPUT_CHARS:],
                           elapsed_seconds=time.perf_counter() - started,
                           timed_out=True, error="Julia execution timed out")
    except OSError as exc:
        return JuliaResult(False, action, exe, returncode=-1,
                           elapsed_seconds=time.perf_counter() - started,
                           error=f"{type(exc).__name__}: {exc}")


def check_source(source: str, filename: str = "untitled.jl",
                 timeout: float = 30.0) -> JuliaResult:
    """Parse, but do not evaluate, a Julia source file."""
    exe = julia_executable()
    if not exe:
        return JuliaResult(False, "check", error="Julia is not installed; syntax check deferred.")
    path = None
    try:
        path, cwd = _temporary_source(source, filename)
        expression = ('Meta.parse("begin\\n" * read(ARGS[1], String) * "\\nend"; '
                      'raise=true); println("Syntax OK")')
        command = [exe, "--startup-file=no", "--history-file=no", "-e", expression,
                   "--", str(path)]
        return _run_command(command, action="check", cwd=cwd, timeout=timeout)
    except Exception as exc:
        return JuliaResult(False, "check", executable=exe,
                           error=f"{type(exc).__name__}: {exc}")
    finally:
        if path is not None:
            path.unlink(missing_ok=True)


def run_source(source: str, filename: str = "untitled.jl",
               timeout: float = DEFAULT_TIMEOUT) -> JuliaResult:
    """Run explicitly selected Julia source in a bounded child process."""
    exe = julia_executable()
    if not exe:
        return JuliaResult(False, "run", error="Julia is not installed. Install Julia or set GROOVEBOX_JULIA_EXECUTABLE.")
    path = None
    try:
        path, cwd = _temporary_source(source, filename)
        command = [exe, "--startup-file=no", "--history-file=no",
                   f"--project={PROJECT_DIR}", str(path)]
        return _run_command(command, action="run", cwd=cwd, timeout=timeout)
    except Exception as exc:
        return JuliaResult(False, "run", executable=exe,
                           error=f"{type(exc).__name__}: {exc}")
    finally:
        if path is not None:
            path.unlink(missing_ok=True)
