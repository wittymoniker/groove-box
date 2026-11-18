"""sos_tools.py — find the external tools Groovebox uses, on any system (sOS, desktop Linux, macOS, Windows).

find(name)      a full argv prefix for the tool, or None. Looks in PATH, then the standard system directories
                (/usr/bin, /bin, /usr/sbin, /sbin, /usr/local/bin, /usr/local/sbin, /opt/sos/bin, /opt/groovebox/bin),
                then a busybox applet of the same name (sOS ships busybox-static), so a trimmed PATH or a missing
                package never makes a tool "not found" when the system still has it.
privileged(argv)  the same command through the system's privilege path (root: as is; else pkexec, else sudo -n).
report()        every tool the app uses: found where, or missing with what stops working and the fallback.
"""
from __future__ import annotations
import os
import sys, shutil, subprocess

DIRS = ("/usr/bin", "/bin", "/usr/sbin", "/sbin", "/usr/local/bin", "/usr/local/sbin", "/opt/sos/bin", "/opt/groovebox/bin")

# tool: (what uses it, fallback when missing)
TOOLS = {
    "dd": ("ISO → USB writer", "built-in Python block writer"),
    "findmnt": ("drive safety checks", "/proc/mounts"),
    "lsblk": ("drive list", "/sys/block"),
    "parted": ("make a data partition after writing a stick", "sfdisk"),
    "sfdisk": ("partitioning", "parted"),
    "wipefs": ("formatting", "zeroing the first MiB"),
    "mkfs.vfat": ("FAT32 format", "mkfs.fat"),
    "mkfs.fat": ("FAT32 format", "mkfs.vfat"),
    "mkfs.ext4": ("ext4 format", "none"),
    "mkfs.exfat": ("exFAT format", "FAT32"),
    "udisksctl": ("unmount as a normal user", "umount through sudo"),
    "umount": ("unmount", "udisksctl"),
    "partprobe": ("re-read partitions", "blockdev --rereadpt / udevadm settle"),
    "udevadm": ("wait for new partitions", "short sleep"),
    "eject": ("safe removal", "sync + unmount"),
    "ffmpeg": ("media import / export", "none (required)"),
    "ffprobe": ("media inspection", "ffmpeg"),
    "mpv": ("external playback", "Qt Multimedia"),
    "pactl": ("audio routing", "wpctl"),
    "wpctl": ("audio routing", "pactl"),
    "amixer": ("hardware volume", "pactl"),
    "aplay": ("audio check", "sounddevice"),
    "arecord": ("mic check", "sounddevice"),
    "nmcli": ("Wi-Fi", "iw"),
    "iw": ("Wi-Fi scan", "nmcli"),
    "rfkill": ("radio on / off", "none"),
    "ip": ("network addresses", "socket"),
    "modprobe": ("drivers", "none"),
    "timedatectl": ("set the clock", "date -s"),
    "hwclock": ("keep the clock across boots", "none"),
    "xdg-open": ("open files with other apps", "Qt desktop services"),
    "lsusb": ("hardware list", "/sys/bus/usb"),
    "sudo": ("privileged actions", "pkexec"),
    "pkexec": ("privileged actions", "sudo"),
    "gcc": ("Program Builder: C", "clang"), "g++": ("Program Builder: C++", "clang++"), "rustc": ("Program Builder: Rust", "none"),
    "go": ("Program Builder: Go", "none"), "julia": ("Program Builder: Julia", "juliacall"), "luajit": ("Lua programs", "built-in LuaJIT (lupa)"),
}


def _busybox():
    for d in ("",) + DIRS:
        p = shutil.which("busybox") if not d else os.path.join(d, "busybox")
        if p and os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def find(name):
    p = shutil.which(name)
    if p:
        return [p]
    for d in DIRS:
        q = os.path.join(d, name)
        if os.path.isfile(q) and os.access(q, os.X_OK):
            return [q]
    bb = _busybox()
    if bb:
        try:
            r = subprocess.run([bb, "--list"], capture_output=True, text=True, timeout=5)
            if name in r.stdout.split():
                return [bb, name]
        except Exception:
            pass
    return None


def path_of(name):
    a = find(name)
    return " ".join(a) if a else None


def check_privileged(argv):
    """R101: a command run with root rights may never be handed a system file or folder to act on.

    argv[0] (the tool itself) and the Python interpreter are exempt; block/character devices are left to
    drive_guard.assert_safe_target, which every raw-device writer already calls.  ``key=value`` arguments
    (dd's if=/of=) are checked by their value.  Raises PermissionError."""
    import stat as _stat
    try:
        import safe_io
    except Exception:
        return argv
    exempt = {os.path.realpath(sys.executable)} if hasattr(sys, "executable") and sys.executable else set()
    for i, a in enumerate(list(argv)):
        if i == 0 or not isinstance(a, str) or a.startswith("-") and "=" not in a:
            continue
        cand = a.split("=", 1)[1] if ("=" in a and not a.startswith("/")) else a
        if not cand.startswith(("/", "~")) and not (os.name == "nt" and len(cand) > 2 and cand[1] == ":"):
            continue
        try:
            st = os.stat(os.path.expanduser(cand))
        except OSError:
            continue
        if _stat.S_ISBLK(st.st_mode) or _stat.S_ISCHR(st.st_mode):
            continue
        if os.path.realpath(os.path.expanduser(cand)) in exempt:
            continue
        if safe_io.is_system_path(cand):
            raise PermissionError(safe_io.protected_message(cand, "change with administrator rights"))
    return argv


def privileged(argv):
    check_privileged(argv)
    try:
        import accounts
        accounts.require("admin", " ".join(map(str, argv[:2])))     # R101: only an owner account runs root commands
    except ImportError:
        pass
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return list(argv)
    for t in ("pkexec", "sudo"):
        a = find(t)
        if a:
            return a + (["-n"] if t == "sudo" else []) + list(argv)
    return list(argv)


def report():
    rows = []
    for name, (use, fb) in sorted(TOOLS.items()):
        a = find(name)
        rows.append({"tool": name, "found": " ".join(a) if a else "", "used_for": use, "fallback": fb})
    return rows


def report_text():
    lines = []
    for r in report():
        lines.append(("✓ %-12s %s" % (r["tool"], r["found"])) if r["found"] else ("✗ %-12s missing — %s → %s" % (r["tool"], r["used_for"], r["fallback"])))
    return "\n".join(lines)


def which(name):
    """Drop-in for shutil.which(name) that also searches the standard system directories (one path, no busybox)."""
    p = shutil.which(name)
    if p:
        return p
    for d in DIRS:
        q = os.path.join(d, name)
        if os.path.isfile(q) and os.access(q, os.X_OK):
            return q
    return None


def ensure_path():
    """Make sure PATH holds the standard system directories (a trimmed PATH must never hide dd, findmnt, …)."""
    cur = os.environ.get("PATH", "").split(os.pathsep) if os.environ.get("PATH") else []
    add = [d for d in DIRS if os.path.isdir(d) and d not in cur]
    if add and os.name == "posix":
        os.environ["PATH"] = os.pathsep.join(cur + add)
    return os.environ.get("PATH", "")


ensure_path()
