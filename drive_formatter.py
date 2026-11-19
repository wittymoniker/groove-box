"""drive_formatter.py — format USB sticks, SD cards and other removable drives (never the host install).

Every operation goes through drive_guard.assert_safe_target: the disk that holds /, /boot, /home, /usr, /opt, /var,
active swap or the live boot medium — and every partition of it — is refused, and only removable / USB / MMC media
are accepted. A whole drive gets a fresh partition table (MBR for FAT32 / exFAT / NTFS so every TV, car stereo and
camera reads it; GPT for ext4 / Btrfs / F2FS) with one partition; a single partition can also be reformatted alone.

File systems (offered when the tool is installed): FAT32 (mkfs.vfat), exFAT (mkfs.exfat), ext4 (mkfs.ext4),
NTFS (mkfs.ntfs), Btrfs (mkfs.btrfs), F2FS (mkfs.f2fs). Root is needed: when not running as root the commands go
through pkexec (or sudo -n) if available. The work runs on a background thread; the window only shows progress.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time

import drive_guard

FILESYSTEMS = (
    ("FAT32", "mkfs.vfat", "msdos", "fat32"),
    ("exFAT", "mkfs.exfat", "msdos", "ntfs"),          # parted has no exfat type; 0x07 (ntfs/exfat) is correct
    ("ext4", "mkfs.ext4", "gpt", "ext4"),
    ("NTFS", "mkfs.ntfs", "msdos", "ntfs"),
    ("Btrfs", "mkfs.btrfs", "gpt", "btrfs"),
    ("F2FS", "mkfs.f2fs", "gpt", "ext4"),
)


def available_filesystems():
    return [fs for fs in FILESYSTEMS if shutil.which(fs[1])]


def _priv(cmd):
    __import__("sos_tools").check_privileged(cmd)   # R101: never hand a system file to a root command
    try:
        __import__("accounts").require("format")     # R101: only an owner formats drives
    except ImportError:
        pass
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return cmd
    if __import__("sos_tools").which("pkexec") and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return ["pkexec"] + cmd
    if __import__("sos_tools").which("sudo"):
        return ["sudo", "-n"] + cmd
    return cmd


def _run(cmd, timeout=600, input_text=None):
    r = subprocess.run(_priv(cmd), capture_output=True, text=True, timeout=timeout, input=input_text)
    if r.returncode != 0:
        raise RuntimeError("%s failed: %s" % (os.path.basename(cmd[0]), (r.stderr or r.stdout or "").strip()[-300:]))
    return r.stdout


def list_drives():
    """Removable drives that may be formatted: [{path, size, model, tran, parts: [{path, size, fstype, label,
    mountpoints}]}]. The system disk and the live boot medium are never listed."""
    try:
        out = subprocess.check_output(["lsblk", "-J", "-b", "-o",
                                       "NAME,PATH,SIZE,TYPE,RM,HOTPLUG,TRAN,MODEL,LABEL,FSTYPE,MOUNTPOINTS"],
                                      text=True, timeout=15)
        data = json.loads(out).get("blockdevices", [])
    except Exception:
        return []
    sysd = drive_guard.system_disks()
    res = []
    for d in data:
        if d.get("type") != "disk":
            continue
        path = d.get("path") or "/dev/" + d.get("name", "")
        if path in sysd:
            continue
        try:
            drive_guard.assert_safe_target(path)
        except PermissionError:
            continue
        parts = []
        for c in d.get("children", []) or []:
            parts.append({"path": c.get("path") or "/dev/" + c.get("name", ""), "size": int(c.get("size") or 0),
                          "fstype": c.get("fstype") or "", "label": c.get("label") or "",
                          "mountpoints": [m for m in (c.get("mountpoints") or []) if m]})
        res.append({"path": path, "size": int(d.get("size") or 0), "model": (d.get("model") or "").strip(),
                    "tran": d.get("tran") or "", "parts": parts})
    return res


def _unmount_all(dev):
    try:
        out = subprocess.check_output(["lsblk", "-n", "-l", "-o", "PATH,MOUNTPOINT", dev], text=True, timeout=15)
    except Exception:
        out = ""
    for ln in out.splitlines():
        bits = ln.split(None, 1)
        if len(bits) == 2 and bits[1].strip():
            if __import__("sos_tools").which("udisksctl"):
                subprocess.run(["udisksctl", "unmount", "-b", bits[0]], capture_output=True, timeout=30)
            if subprocess.run(["findmnt", "-n", bits[0]], capture_output=True).returncode == 0:
                _run(["umount", bits[0]], timeout=60)


def _mkfs_cmd(fs_name, mkfs, part, label):
    lab = (label or "GROOVEBOX").strip() or "GROOVEBOX"
    if fs_name == "FAT32":
        return [mkfs, "-F", "32", "-n", lab.upper()[:11], part]
    if fs_name == "exFAT":
        return [mkfs, "-n", lab[:15], part]
    if fs_name == "ext4":
        return [mkfs, "-F", "-L", lab[:16], part]
    if fs_name == "NTFS":
        return [mkfs, "-f", "-L", lab[:32], part]
    if fs_name == "Btrfs":
        return [mkfs, "-f", "-L", lab[:255], part]
    if fs_name == "F2FS":
        return [mkfs, "-f", "-l", lab[:512], part]
    raise ValueError("unknown file system %s" % fs_name)


def _fs(fs_name):
    for fs in FILESYSTEMS:
        if fs[0].lower() == str(fs_name).lower():
            if not shutil.which(fs[1]):
                raise RuntimeError("%s is not installed (%s)" % (fs[0], fs[1]))
            return fs
    raise ValueError("unknown file system %s" % fs_name)


def format_partition(part, fs_name="FAT32", label="GROOVEBOX", progress=None):
    """Reformat one partition of a removable drive."""
    part = str(part)
    drive_guard.assert_safe_target(part)
    name, mkfs, _table, _ptype = _fs(fs_name)
    progress and progress("unmounting " + part)
    _unmount_all(part)
    progress and progress("writing %s on %s" % (name, part))
    _run(_mkfs_cmd(name, shutil.which(mkfs), part, label), timeout=1800)
    _settle()
    _seed_books(part, progress)
    return {"device": part, "fs": name, "label": label}


def format_drive(dev, fs_name="FAT32", label="GROOVEBOX", progress=None):
    """New partition table + one partition spanning the drive, formatted with `fs_name`."""
    dev = drive_guard.assert_safe_target(str(dev))
    if drive_guard._disk_of(dev) != dev:
        raise PermissionError("%s is a partition; use format_partition for one partition" % dev)
    name, mkfs, table, ptype = _fs(fs_name)
    progress and progress("unmounting " + dev)
    _unmount_all(dev)
    progress and progress("wiping old signatures")
    if __import__("sos_tools").which("wipefs"):
        _run(["wipefs", "-a", dev], timeout=120)
    progress and progress("new %s partition table" % ("MBR" if table == "msdos" else "GPT"))
    if __import__("sos_tools").which("parted"):
        _run(["parted", "-s", dev, "mklabel", table], timeout=60)
        _run(["parted", "-s", "-a", "optimal", dev, "mkpart", "primary", ptype, "1MiB", "100%"], timeout=60)
    elif __import__("sos_tools").which("sfdisk"):
        typ = "c" if name == "FAT32" else ("7" if name in ("exFAT", "NTFS") else "83")
        _run(["sfdisk", dev], timeout=60, input_text=("label: %s\n,,%s\n" % ("dos" if table == "msdos" else "gpt",
                                                                             typ if table == "msdos" else "L")))
    else:
        raise RuntimeError("parted or sfdisk is needed to partition the drive")
    _settle(dev)
    part = _first_partition(dev)
    if not part:
        raise RuntimeError("the new partition did not appear")
    progress and progress("writing %s on %s" % (name, part))
    _run(_mkfs_cmd(name, shutil.which(mkfs), part, label), timeout=1800)
    _settle()
    _seed_books(part, progress)
    return {"device": dev, "partition": part, "fs": name, "label": label}


def _settle(dev=None):
    if __import__("sos_tools").which("partprobe") and dev:
        subprocess.run(_priv(["partprobe", dev]), capture_output=True, timeout=30)
    if __import__("sos_tools").which("udevadm"):
        subprocess.run(["udevadm", "settle", "--timeout=10"], capture_output=True, timeout=15)
    time.sleep(0.3)


def _first_partition(dev):
    for _ in range(20):
        try:
            out = subprocess.check_output(["lsblk", "-n", "-l", "-o", "PATH,TYPE", dev], text=True, timeout=10)
            parts = [ln.split()[0] for ln in out.splitlines() if ln.split()[-1:] == ["part"]]
            if parts:
                return parts[0]
        except Exception:
            pass
        time.sleep(0.25)
    return None


def _human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return "%.1f %s" % (n, unit) if unit != "B" else "%d B" % n
        n /= 1024.0


def make_page(app=None):
    """A File Studio tab: removable drives and their partitions, file system, label, format buttons."""
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
    from PyQt6.QtWidgets import (QComboBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton,
                                 QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

    class _Sig(QObject):
        msg = pyqtSignal(str)
        done = pyqtSignal(str)

    page = QWidget(); lay = QVBoxLayout(page)
    lay.addWidget(QLabel("💽 Removable drives (USB sticks, SD cards, USB disks). The computer's own disk and the "
                         "drive this system booted from are never listed and cannot be formatted."))
    tree = QTreeWidget(); tree.setHeaderLabels(["device", "size", "file system", "label", "mounted at", "model"])
    tree.setColumnWidth(0, 160)
    lay.addWidget(tree, 1)
    row = QHBoxLayout(); lay.addLayout(row)
    fs = QComboBox()
    for f in available_filesystems():
        fs.addItem(f[0])
    if fs.count() == 0:
        fs.addItem("(no mkfs tools installed)")
    lab = QLineEdit("GROOVEBOX"); lab.setFixedWidth(140)
    b_drive = QPushButton("Format whole drive…"); b_part = QPushButton("Format partition…"); b_ref = QPushButton("Refresh")
    b_iso = QPushButton("💿 Make install media…")
    b_iso.setToolTip("Write a Groovebox / sOS ISO to the selected USB stick as a bootable installer (this system's own "
                     "ISO by default), then optionally add a FAT32 data partition in the free space")
    for x in (QLabel("File system"), fs, QLabel("Label"), lab, b_drive, b_part, b_iso, b_ref):
        row.addWidget(x)
    row.addStretch(1)
    status = QLabel(""); lay.addWidget(status)
    sig = _Sig(page); sig.msg.connect(status.setText)

    def refresh():
        tree.clear()
        for d in list_drives():
            it = QTreeWidgetItem(tree, [d["path"], _human(d["size"]), "", "", "", "%s %s" % (d["model"], d["tran"])])
            it.setData(0, Qt.ItemDataRole.UserRole, ("drive", d["path"]))
            for p in d["parts"]:
                c = QTreeWidgetItem(it, [p["path"], _human(p["size"]), p["fstype"], p["label"], ", ".join(p["mountpoints"]), ""])
                c.setData(0, Qt.ItemDataRole.UserRole, ("part", p["path"]))
            it.setExpanded(True)
        if tree.topLevelItemCount() == 0:
            status.setText("No removable drive found — plug in a USB stick or SD card, then Refresh.")

    def _selected(kind):
        it = tree.currentItem()
        if it is None:
            return None
        k, path = it.data(0, Qt.ItemDataRole.UserRole) or (None, None)
        if kind == "drive" and k == "part":
            return it.parent().data(0, Qt.ItemDataRole.UserRole)[1]
        return path if k == kind else None

    def _go(kind):
        target = _selected(kind)
        if not target:
            status.setText("Select a %s first." % ("drive" if kind == "drive" else "partition"))
            return
        fsn = fs.currentText()
        if fsn.startswith("("):
            return
        txt, ok = QInputDialog.getText(page, "Erase everything on %s" % target,
                                       "Everything on %s will be erased and it becomes %s \"%s\".\n"
                                       "Type the device name to confirm (%s):" % (target, fsn, lab.text(), target))
        if not ok or txt.strip() != target:
            status.setText("Not formatted (confirmation did not match).")
            return
        b_drive.setEnabled(False); b_part.setEnabled(False)

        def work():
            try:
                fn = format_drive if kind == "drive" else format_partition
                r = fn(target, fsn, lab.text(), progress=sig.msg.emit)
                sig.done.emit("✔ %s is now %s \"%s\"" % (r.get("partition") or r["device"], r["fs"], r["label"]))
            except Exception as exc:
                sig.done.emit("⚠ %s" % exc)
        threading.Thread(target=work, name="drive-format", daemon=True).start()

    def _done(msg):
        status.setText(msg); b_drive.setEnabled(True); b_part.setEnabled(True); refresh()
    sig.done.connect(_done)
    def _iso():
        from PyQt6.QtWidgets import QFileDialog
        target = _selected("drive")
        if not target:
            status.setText("Select the USB drive first.")
            return
        default = ""
        try:
            import operation_station_transfer as _ost
            p = _ost.find_finished_iso() or _ost.ensure_self_iso()
            default = str(p) if p else ""
        except Exception:
            _ost = None
        iso, _f = QFileDialog.getOpenFileName(page, "ISO to write", default or os.path.expanduser("~"), "ISO image (*.iso)")
        if not iso or _ost is None:
            return
        txt, ok = QInputDialog.getText(page, "Erase %s" % target, "Everything on %s is replaced by the bootable "
                                       "installer %s.\nType the device name to confirm (%s):" % (target, os.path.basename(iso), target))
        if not ok or txt.strip() != target:
            status.setText("Not written (confirmation did not match).")
            return
        data_part = QMessageBox.question(page, "Data partition", "Add a FAT32 data partition in the free space after "
                                         "the installer (for projects and exports)?") == QMessageBox.StandardButton.Yes
        b_iso.setEnabled(False)

        def work():
            try:
                sig.msg.emit("writing %s → %s …" % (os.path.basename(iso), target))
                _ost.write_bootable_installer(iso, target)
                if data_part:
                    sig.msg.emit("adding the data partition…")
                    _ost.reclaim_usb_space(target)
                sig.done.emit("✔ install media ready on %s" % target)
            except Exception as exc:
                sig.done.emit("⚠ %s" % exc)
        threading.Thread(target=work, name="install-media", daemon=True).start()

    def _done_iso(msg):
        b_iso.setEnabled(True)
    sig.done.connect(_done_iso)
    b_iso.clicked.connect(_iso)
    b_drive.clicked.connect(lambda: _go("drive")); b_part.clicked.connect(lambda: _go("part")); b_ref.clicked.connect(refresh)
    QTimer.singleShot(0, refresh)
    return page


def _seed_books(part, progress=None):
    """R101: put the author's book (PDF, raw text, ASCII) in a Groovebox/ folder on every drive formatted here.
    Mounts through udisks as the user, copies, unmounts. Never fails the format."""
    import glob, re, subprocess
    here = os.path.dirname(os.path.abspath(__file__))
    srcs = [p for d in (os.path.join(here, "docs", "books"), "/usr/share/doc/groovebox/books") for p in glob.glob(os.path.join(d, "*"))]
    if not srcs:
        return
    try:
        ud = __import__("sos_tools").which("udisksctl")
        if not ud:
            return
        _settle(part)
        r = subprocess.run([ud, "mount", "-b", part, "--no-user-interaction"], capture_output=True, text=True, timeout=30)
        m = re.search(r" at (.+?)\.?$", (r.stdout or "").strip())
        if not m:
            return
        dest = os.path.join(m.group(1), "Groovebox"); os.makedirs(dest, exist_ok=True)
        seen = set()
        for p in srcs:
            if os.path.basename(p) not in seen:
                shutil.copyfile(p, os.path.join(dest, os.path.basename(p))); seen.add(os.path.basename(p))
        progress and progress("added the book to Groovebox/ on " + part)
        subprocess.run([ud, "unmount", "-b", part, "--no-user-interaction"], capture_output=True, text=True, timeout=30)
    except Exception:
        pass
