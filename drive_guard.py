"""drive_guard.py — never touch the OS disk.

GROOVEBOX_DRIVE_GUARD_20261111
Format, partition, wipe, and bootable-write tools may only target a removable
drive. The disk that holds /, /boot, /home, /usr, or /opt — and every partition
of that disk — is refused, whatever its name.
"""
from __future__ import annotations

import os
import re


_SYS_MOUNTS = ("/", "/boot", "/boot/efi", "/home", "/usr", "/opt", "/var")


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except Exception:
        return ""


def _disk_of(dev: str) -> str:
    """Whole-disk name for a partition (/dev/nvme0n1p2 -> /dev/nvme0n1)."""
    dev = str(dev or "").strip()
    dev = re.sub(r"p\d+$", "", dev)          # nvme / mmc
    dev = re.sub(r"\d+$", "", dev)           # sdX1
    return dev


def system_disks() -> set:
    """Every whole disk that holds an OS mount."""
    disks = set()
    try:
        with open("/proc/self/mountinfo", "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        lines = []
    for line in lines:
        parts = line.split()
        if len(parts) < 5:
            continue
        mount = parts[4]
        # source is after the ' - ' separator
        if " - " not in line:
            continue
        tail = line.split(" - ", 1)[1].split()
        src = tail[1] if len(tail) > 1 else ""
        if mount in _SYS_MOUNTS or mount.startswith("/boot"):
            if src.startswith("/dev/"):
                disks.add(_disk_of(src))
    # Fallback names if mountinfo was empty.
    if not disks:
        for name in ("nvme0n1", "sda", "vda", "mmcblk0"):
            if os.path.exists("/dev/" + name):
                disks.add("/dev/" + name)
    return disks


def is_removable(dev: str) -> bool:
    disk = os.path.basename(_disk_of(dev))
    flag = _read(os.path.join("/sys/class/block", disk, "removable"))
    return flag == "1"


def assert_safe_target(dev: str) -> str:
    """Raise PermissionError if dev is the OS disk or any partition of it.

    Returns the normalized device path when it is a removable non-system disk.
    """
    dev = str(dev or "").strip()
    if not dev.startswith("/dev/"):
        raise PermissionError("Refusing non-device path: %s" % dev)
    disk = _disk_of(dev)
    sys_disks = system_disks()
    if disk in sys_disks or dev in sys_disks:
        raise PermissionError(
            "Refusing the OS disk %s. Format and partition tools cannot touch the system drive or any of its partitions." % disk)
    if not is_removable(dev):
        raise PermissionError(
            "Refusing %s: it is not a removable drive. Only USB / SD sticks can be formatted or repartitioned." % dev)
    return dev


def assert_safe_path(path: str) -> str:
    """Raise PermissionError if a file operation would land on the OS disk root system dirs."""
    path = os.path.realpath(os.path.expanduser(str(path or "")))
    blocked = ("/boot", "/usr", "/opt", "/var", "/etc", "/bin", "/sbin", "/lib", "/lib64")
    if path == "/" or any(path == b or path.startswith(b + os.sep) for b in blocked):
        raise PermissionError("Refusing a file operation on a system path: %s" % path)
    return path
