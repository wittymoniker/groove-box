#!/usr/bin/env python3
"""disc_burn.py — GROOVEBOX_DISC_BURN_20261112

Produce an ISO of this Groovebox and burn it to CD / DVD / BD from Performance ▸ Drive / Clone.

  optical_drives()          [{"device": "/dev/sr0", "model": ..., "media": bool}]
  burner_tool()             first of xorriso · growisofs · wodim · cdrecord on PATH
  build_bootable_iso()      runs BUILD_ISO/RUN_ME_ZERO_STATE.sh (root via pkexec when needed),
                            streaming every line to the log callback; returns the finished ISO
  build_source_iso()        no root needed: an ISO9660 + Rock Ridge + Joliet data disc holding
                            this source tree (an "update disc": another Groovebox finds it under
                            Drive / Clone ▸ Update from drive) plus the newest bootable ISO when
                            it fits the chosen media size
  burn(iso, device)         burns with the best available tool; parses its progress lines;
                            verify=True reads the disc back and compares SHA-256
  plan(...)                 the exact argv that would run (for tests / dry runs)

Stdlib only.  Every external command is an argv list (never a shell string).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

APP_ROOT = Path(__file__).resolve().parent
Log = Optional[Callable[[str], None]]
Progress = Optional[Callable[[str, int, int], None]]
MEDIA_BYTES = {"CD 700 MB": 700 * 1000 ** 2, "DVD 4.7 GB": 4_700_372_992, "DVD DL 8.5 GB": 8_543_666_176,
               "BD 25 GB": 25_025_314_816, "BD 50 GB": 50_050_629_632}
_PCT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")


def _emit(log: Log, line: str) -> None:
    if log:
        try:
            log(line)
        except Exception:
            pass


def optical_drives() -> List[Dict]:
    out: List[Dict] = []
    try:
        r = subprocess.run(["lsblk", "-J", "-d", "-o", "NAME,TYPE,MODEL,SIZE"], capture_output=True, text=True, timeout=10)
        for d in json.loads(r.stdout or "{}").get("blockdevices", []):
            if d.get("type") == "rom":
                out.append({"device": "/dev/" + d["name"], "model": (d.get("model") or "optical drive").strip(),
                            "media": bool(d.get("size") and d.get("size") not in ("0B", "0"))})
    except Exception:
        pass
    if not out:
        for p in sorted(Path("/dev").glob("sr[0-9]*")):
            out.append({"device": str(p), "model": "optical drive", "media": True})
    return out


def burner_tool() -> Optional[str]:
    for t in ("xorriso", "growisofs", "wodim", "cdrecord"):
        if shutil.which(t):
            return t
    return None


def iso_tool() -> Optional[str]:
    for t in ("xorriso", "genisoimage", "mkisofs"):
        if shutil.which(t):
            return t
    return None


def plan_burn(iso: str, device: str, tool: Optional[str] = None, speed: int = 0) -> List[str]:
    tool = tool or burner_tool()
    if tool is None:
        raise RuntimeError("No disc burner found. Install xorriso (or growisofs / wodim).")
    sp = [f"speed={speed}"] if speed else []
    if tool == "xorriso":
        return ["xorriso", "-as", "cdrecord", "-v", f"dev={device}", "-dao", "-eject", *sp, iso]
    if tool == "growisofs":
        return ["growisofs", "-dvd-compat", *([f"-speed={speed}"] if speed else []), "-Z", f"{device}={iso}"]
    return [tool, "-v", f"dev={device}", "-dao", "-eject", *sp, iso]


def _run_stream(cmd: List[str], log: Log, progress: Progress, phase: str, cwd=None, env=None, timeout=None) -> int:
    _emit(log, "$ " + " ".join(cmd))
    p = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, bufsize=1, errors="replace")
    t0 = time.monotonic(); last = -1
    assert p.stdout is not None
    for raw in iter(p.stdout.readline, ""):
        # burners redraw progress with \r; keep the newest fragment
        line = raw.rstrip("\n").split("\r")[-1].strip()
        if not line:
            continue
        _emit(log, line)
        m = _PCT.search(line)
        if m:
            pct = min(100, int(float(m.group(1))))
            if pct != last:
                last = pct
                if progress:
                    progress(phase, pct, 100)
        if timeout and time.monotonic() - t0 > timeout:
            p.kill(); _emit(log, f"timed out after {timeout:.0f} s"); return 124
    return p.wait()


def _read_back_sha(device: str, nbytes: int, progress: Progress) -> str:
    h = hashlib.sha256(); done = 0
    with open(device, "rb") as f:
        while done < nbytes:
            b = f.read(min(1 << 22, nbytes - done))
            if not b:
                break
            h.update(b); done += len(b)
            if progress:
                progress("verifying", int(100 * done / max(1, nbytes)), 100)
    if done != nbytes:
        raise IOError(f"read back only {done} of {nbytes} bytes")
    return h.hexdigest()


def sha256_file(path: str, progress: Progress = None) -> str:
    h = hashlib.sha256(); total = os.path.getsize(path); done = 0
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b); done += len(b)
            if progress:
                progress("hashing", int(100 * done / max(1, total)), 100)
    return h.hexdigest()


def burn(iso: str, device: str, *, speed: int = 0, verify: bool = True, log: Log = None,
         progress: Progress = None, tool: Optional[str] = None) -> Dict:
    iso = str(Path(iso).expanduser().resolve())
    if not os.path.isfile(iso):
        raise FileNotFoundError(iso)
    if not re.match(r"^/dev/(sr\d+|cdrom\d*|dvd\d*|scd\d+)$", device) and not os.environ.get("GROOVEBOX_BURN_ANY_DEVICE"):
        raise PermissionError(f"{device} is not an optical drive (expected /dev/sr0 …). USB sticks use 'Write bootable USB'.")
    want = sha256_file(iso, progress) if verify else ""
    rc = _run_stream(plan_burn(iso, device, tool, speed), log, progress, "burning")
    if rc != 0:
        raise RuntimeError(f"burner exited {rc} (see log) — blank/erasable disc inserted and large enough?")
    res = {"ok": True, "iso": iso, "device": device, "sha256": want, "verified": False}
    if verify:
        try:
            if __import__("sos_tools").which("eject"):
                subprocess.run(["eject", "-t", device], capture_output=True, timeout=30)   # close tray for read-back
            time.sleep(2)
            got = _read_back_sha(device, os.path.getsize(iso), progress)
            res["verified"] = got == want
            if not res["verified"]:
                res["ok"] = False; res["message"] = "read-back checksum differs: the disc is bad"
        except Exception as exc:
            res["message"] = f"burned; read-back skipped ({exc})"
    return res


# --------------------------------------------------------------------------- building ISOs
def iso_out_dir() -> Path:
    try:
        import groovebox_paths
        p = Path(groovebox_paths.base_dir()) / "iso"
    except Exception:
        p = Path.home() / "Groovebox" / "iso"
    p.mkdir(parents=True, exist_ok=True)
    return p


def plan_bootable(root: Path = APP_ROOT) -> List[str]:
    script = Path(root) / "BUILD_ISO" / "RUN_ME_ZERO_STATE.sh"
    if not script.is_file():
        raise FileNotFoundError("BUILD_ISO/RUN_ME_ZERO_STATE.sh is not in this installation")
    cmd = ["bash", str(script)]
    if os.geteuid() != 0:
        if __import__("sos_tools").which("pkexec"):
            # pkexec drops the environment; pass the answers the builder would otherwise prompt for
            cmd = ["pkexec", "env", "GROOVEBOX_SECURE_BOOT=0", f"HOME={Path.home()}", f"PATH={os.environ.get('PATH', '')}"] + cmd
        elif __import__("sos_tools").which("sudo"):
            cmd = ["sudo", "-n", "env", "GROOVEBOX_SECURE_BOOT=0"] + cmd
    return cmd


def build_bootable_iso(root: Path = APP_ROOT, log: Log = None, progress: Progress = None) -> Dict:
    t0 = time.time()
    env = dict(os.environ, GROOVEBOX_SECURE_BOOT="0")
    rc = _run_stream(plan_bootable(root), log, progress, "building", cwd=str(root), env=env, timeout=4 * 3600)
    if rc != 0:
        return {"ok": False, "message": f"bootable ISO builder exited {rc} (see log; it needs x86_64, root and the build tools — "
                                        "'Check builder' lists what is missing)", "iso": ""}
    try:
        from operation_station_transfer import find_finished_iso
        iso = find_finished_iso(Path(root))
    except Exception:
        iso = None
    if iso is None or os.path.getmtime(iso) < t0 - 5:
        return {"ok": False, "message": "builder finished but no new ISO was found", "iso": ""}
    return {"ok": True, "message": "bootable ISO built", "iso": str(iso)}


_SRC_SKIP = {"__pycache__", ".git", ".pytest_cache", "exports", "renders", "projects", "samples", "user_data",
             "node_modules", ".venv", "venv", "dist", "build"}


def plan_source_iso(out: str, root: Path = APP_ROOT, extra: Optional[List[str]] = None, volid: str = "GROOVEBOX") -> List[str]:
    tool = iso_tool()
    if tool is None:
        raise RuntimeError("No ISO maker found. Install xorriso (or genisoimage).")
    excl = []
    for d in sorted(_SRC_SKIP):
        excl += ["-m", d]
    name = Path(root).name or "MATH_GROOVEBOX-v3"
    graft = [f"{name}={root}"] + [f"BOOTABLE/{Path(e).name}={e}" for e in (extra or [])]
    head = ["xorriso", "-as", "mkisofs"] if tool == "xorriso" else [tool]
    return head + ["-r", "-J", "-joliet-long", "-V", volid[:32], "-iso-level", "3", *excl,
                   "-o", out, "-graft-points", *graft]


def build_source_iso(root: Path = APP_ROOT, media: str = "DVD 4.7 GB", include_bootable: bool = True,
                     log: Log = None, progress: Progress = None, out: Optional[str] = None) -> Dict:
    root = Path(root)
    out = out or str(iso_out_dir() / f"Groovebox-source-{time.strftime('%Y%m%d-%H%M%S')}.iso")
    extra: List[str] = []
    cap = MEDIA_BYTES.get(media, MEDIA_BYTES["DVD 4.7 GB"])
    if include_bootable:
        try:
            from operation_station_transfer import find_finished_iso
            boot = find_finished_iso(root)
            if boot and os.path.getsize(boot) < cap * 0.8:
                extra.append(str(boot))
        except Exception:
            pass
    # README so the disc explains itself on any computer
    readme = iso_out_dir() / "README-GROOVEBOX-DISC.txt"
    __import__("safe_io").atomic_write_text(readme, "Mathematician's Groovebox — source / update disc\n\n"
                      "Groovebox: Performance ▸ Drive / Clone ▸ Update from drive ▸ Scan, then Apply.\n"
                      "Any computer: copy the MATH_GROOVEBOX-v3 folder and run  python3 run_groovebox.py\n"
                      "BOOTABLE/ (when present) holds the bootable appliance ISO for a USB stick.\n", encoding="utf-8")
    extra.append(str(readme))
    cmd = plan_source_iso(out, root, extra=[e for e in extra if e != str(readme)])
    cmd.append(f"README.txt={readme}")
    rc = _run_stream(cmd, log, progress, "making ISO", cwd=str(root), timeout=3600)
    if rc != 0 or not os.path.isfile(out):
        return {"ok": False, "message": f"ISO maker exited {rc} (see log)", "iso": ""}
    size = os.path.getsize(out)
    fits = size <= cap
    return {"ok": True, "iso": out, "bytes": size, "fits": fits, "media": media,
            "message": ("source ISO ready" if fits else f"source ISO is {size / 1e9:.2f} GB — larger than {media}")}
