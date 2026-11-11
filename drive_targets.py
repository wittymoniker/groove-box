"""GROOVEBOX_DRIVE_TARGETS_20261102: USB sticks, SD cards and other drives as first-class save targets.

Three easy ways to get a project, an export or any file onto a drive:

  1. Every Save / Open / Choose-folder dialog shows the connected drives in its sidebar
     (install_file_dialog_support() wraps the QFileDialog static helpers once, at startup).
  2. The "Copy to USB / SD" button (main window and Performance) copies the project, the latest
     exports or any files/folder to a chosen drive, checks every file by SHA-256 and can eject.
  3. "Also copy saves to a connected drive" (Compatibility settings) copies each project save to the
     first connected drive automatically.

Nothing here deletes anything on the drive. A same-named file is replaced only after the new copy has
been written, flushed and verified.
"""
import hashlib
import os
import re
import shutil
import subprocess
import threading
import time

_MOUNT_ROOTS = ("/media/", "/run/media/", "/mnt/", "/Volumes/")
_SKIP_FS = {"iso9660", "squashfs", "tmpfs", "devtmpfs", "overlay", "proc", "sysfs", "cgroup", "cgroup2",
            "ramfs", "autofs", "fuse.portal", "nfs", "nfs4", "cifs", "9p"}
_BAD_NAME_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')


def _unescape(s):
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), s)


def _block_removable(source, sys_class_block="/sys/class/block"):
    """True when the block device behind `source` (e.g. /dev/sdb1) is a USB / SD / removable disk."""
    name = os.path.basename(str(source))
    if not name:
        return False
    if name.startswith("mmcblk"):
        return True
    real = os.path.realpath(os.path.join(sys_class_block, name))
    for cand in (os.path.join(real, "removable"), os.path.join(os.path.dirname(real), "removable")):
        try:
            with open(cand, "r") as f:
                if f.read().strip() == "1":
                    return True
        except OSError:
            pass
    return "/usb" in real


def _windows_drives():
    """Windows: removable drive letters (USB sticks, SD cards) — GetDriveTypeW == DRIVE_REMOVABLE (2)."""
    rows = []
    try:
        import ctypes, string
        k32 = ctypes.windll.kernel32
        mask = k32.GetLogicalDrives()
        for i, letter in enumerate(string.ascii_uppercase):
            if not (mask >> i) & 1:
                continue
            root = letter + ":\\"
            if k32.GetDriveTypeW(ctypes.c_wchar_p(root)) != 2:
                continue
            if not os.path.isdir(root) or not os.access(root, os.W_OK):
                continue
            try:
                du = shutil.disk_usage(root)
            except OSError:
                continue
            name = ctypes.create_unicode_buffer(261)
            try:
                k32.GetVolumeInformationW(ctypes.c_wchar_p(root), name, 261, None, None, None, None, 0)
            except Exception:
                pass
            rows.append({"path": root, "label": (name.value or "USB") + " (" + letter + ":)", "device": letter + ":",
                         "fstype": "", "free": int(du.free), "total": int(du.total), "kind": "USB drive"})
    except Exception:
        pass
    return rows


def _mac_drives(volumes="/Volumes"):
    """macOS: every writable volume under /Volumes except the boot disk."""
    rows = []
    try:
        boot = os.stat("/").st_dev
        for name in sorted(os.listdir(volumes)):
            p = os.path.join(volumes, name)
            try:
                if os.path.islink(p) or os.stat(p).st_dev == boot or not os.access(p, os.W_OK):
                    continue
                du = shutil.disk_usage(p)
            except OSError:
                continue
            rows.append({"path": p, "label": name, "device": "", "fstype": "", "free": int(du.free),
                         "total": int(du.total), "kind": "USB drive"})
    except OSError:
        pass
    return rows


def removable_drives(mountinfo="/proc/self/mountinfo", sys_class_block="/sys/class/block"):
    """Writable, mounted removable drives: [{path,label,device,fstype,free,total,kind}]."""
    import sys as _sys
    if _sys.platform.startswith("win"):
        return _windows_drives()
    if _sys.platform == "darwin":
        return _mac_drives()
    rows, seen = [], set()
    try:
        with open(mountinfo, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return rows
    for line in lines:
        try:
            left, right = line.split(" - ", 1)
            lf = left.split()
            mount = _unescape(lf[4])
            opts = lf[5].split(",")
            fstype, source = right.split()[0], right.split()[1]
        except (ValueError, IndexError):
            continue
        if mount in seen or "ro" in opts or fstype in _SKIP_FS:
            continue
        under = mount.rstrip("/") + "/"
        in_roots = under.startswith(_MOUNT_ROOTS)
        # a removable device mounted somewhere unusual still counts; a plain /mnt entry must be a real device
        real_dev = str(source).startswith("/dev/")
        if not ((in_roots and real_dev) or (real_dev and _block_removable(source, sys_class_block))):
            continue
        if not os.path.isdir(mount) or not os.access(mount, os.W_OK):
            continue
        try:
            du = shutil.disk_usage(mount)
        except OSError:
            continue
        name = os.path.basename(str(source))
        kind = "SD card" if name.startswith("mmcblk") else "USB drive"
        seen.add(mount)
        rows.append({"path": mount, "label": os.path.basename(mount.rstrip("/")) or mount, "device": str(source),
                     "fstype": fstype, "free": int(du.free), "total": int(du.total), "kind": kind})
    rows.sort(key=lambda r: r["path"])
    return rows


def human_bytes(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0


def describe_drive(row):
    return f"{row['label']} · {row['kind']} · {human_bytes(row['free'])} free of {human_bytes(row['total'])} · {row['path']}"


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_name(name, fat=True):
    return _BAD_NAME_CHARS.sub("_", name) if fat else name


def _iter_files(sources):
    for src in sources:
        src = str(src)
        if os.path.isdir(src):
            base = os.path.dirname(src.rstrip("/"))
            for root, _dirs, files in os.walk(src):
                for fn in files:
                    full = os.path.join(root, fn)
                    yield full, os.path.relpath(full, base)
        elif os.path.isfile(src):
            yield src, os.path.basename(src)


def copy_to_drive(sources, drive_root, subfolder="Groovebox", verify=True, progress=None):
    """Copy files / folders to <drive>/<subfolder>/. Returns a report dict; never raises for one bad file."""
    report = {"copied": [], "failed": [], "bytes": 0, "dest": "", "verified": bool(verify)}
    dest_root = os.path.join(str(drive_root), subfolder) if subfolder else str(drive_root)
    report["dest"] = dest_root
    files = list(_iter_files(sources))
    need = 0
    for full, _rel in files:
        try:
            need += os.path.getsize(full)
        except OSError:
            pass
    try:
        free = shutil.disk_usage(str(drive_root)).free
    except OSError as exc:
        report["failed"].append((str(drive_root), f"drive not readable: {exc}"))
        return report
    if need > free:
        report["failed"].append((str(drive_root), f"not enough space: need {human_bytes(need)}, {human_bytes(free)} free"))
        return report
    try:
        os.makedirs(dest_root, exist_ok=True)
    except OSError as exc:
        report["failed"].append((dest_root, str(exc)))
        return report
    for i, (full, rel) in enumerate(files):
        parts = [_safe_name(p) for p in rel.replace("\\", "/").split("/") if p]
        target = os.path.join(dest_root, *parts)
        tmp = target + ".part"
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(full, "rb") as src, open(tmp, "wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
                dst.flush()
                os.fsync(dst.fileno())
            if verify and _sha256(full) != _sha256(tmp):
                raise OSError("checksum mismatch after copy")
            os.replace(tmp, target)
            report["copied"].append(target)
            report["bytes"] += os.path.getsize(target)
        except Exception as exc:
            report["failed"].append((full, str(exc)))
            try:
                os.remove(tmp)
            except OSError:
                pass
        if progress:
            try:
                progress(i + 1, len(files), full)
            except Exception:
                pass
    try:
        os.sync()
    except Exception:
        pass
    return report


def report_text(report):
    lines = [f"Copied {len(report['copied'])} file(s), {human_bytes(report['bytes'])} to {report['dest']}"
             + (" (each file checked)" if report.get("verified") else "")]
    for path, why in report["failed"]:
        lines.append(f"FAILED {path}: {why}")
    return "\n".join(lines)


def eject(drive_root):
    """Flush, unmount and (if possible) power off. Returns (ok, message)."""
    try:
        os.sync()
    except Exception:
        pass
    dev = ""
    for row in removable_drives():
        if row["path"] == str(drive_root):
            dev = row["device"]
    for cmd in (["udisksctl", "unmount", "-b", dev] if dev and shutil.which("udisksctl") else None,
                ["umount", str(drive_root)] if shutil.which("umount") else None):
        if not cmd:
            continue
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                if cmd[0] == "udisksctl" and dev:
                    try:
                        subprocess.run(["udisksctl", "power-off", "-b", re.sub(r"p?\d+$", "", dev)],
                                       capture_output=True, text=True, timeout=15)
                    except Exception:
                        pass
                return True, "Safe to remove."
        except Exception:
            continue
    return False, "Could not unmount automatically; use the desktop's eject before removing it."


def copy_in_background(sources, drive_root, done, subfolder="Groovebox", verify=True, progress=None):
    """Run copy_to_drive on a worker thread; done(report) is called from that thread."""
    def work():
        rep = copy_to_drive(sources, drive_root, subfolder, verify, progress)
        try:
            done(rep)
        except Exception:
            pass
    t = threading.Thread(target=work, name="groovebox-drive-copy", daemon=True)
    t.start()
    return t


def auto_copy_enabled():
    try:
        import compat_settings
        return bool(compat_settings.load().get("auto_copy_to_drive"))
    except Exception:
        return False


def auto_copy(path, done=None):
    """Copy a just-saved file to the first connected drive when the setting is on. Returns True if started."""
    if not path or not auto_copy_enabled() or not os.path.isfile(str(path)):
        return False
    drives = removable_drives()
    if not drives:
        return False
    copy_in_background([path], drives[0]["path"], done or (lambda rep: None))
    return True


# ---- file-dialog sidebar -------------------------------------------------------------------------
_INSTALLED = False


def mount_places():
    """Folders where USB sticks / SD cards appear, for file-dialog sidebars: /media/<user>, /run/media/<user>,
    /media, /mnt, /Volumes — whichever exist (Windows drive letters show in the dialog's own sidebar)."""
    import getpass
    try:
        user = getpass.getuser()
    except Exception:
        user = ""
    out = []
    for p in ([f"/media/{user}", f"/run/media/{user}"] if user else []) + ["/media", "/mnt", "/Volumes"]:
        if os.path.isdir(p) and p not in out and not any(p.startswith(q + "/") for q in out):
            out.append(p)
    return out


def install_file_dialog_support():
    """Make Save / Open / Folder dialogs list connected drives. Idempotent; falls back to the stock dialog."""
    global _INSTALLED
    if _INSTALLED:
        return True
    try:
        from PyQt6.QtWidgets import QFileDialog
        from PyQt6.QtCore import QUrl
    except Exception:
        return False
    orig_save = QFileDialog.getSaveFileName
    orig_open = QFileDialog.getOpenFileName
    orig_many = QFileDialog.getOpenFileNames
    orig_dir = QFileDialog.getExistingDirectory

    def build(parent, caption, directory, filt, initial_filter, options, mode, accept):
        # Never enumerate removable devices while constructing a GUI dialog.
        # disk_usage()/mount probing can block on a failing or sleeping USB
        # filesystem. Expose stable mount roots in the sidebar instead; actual
        # drive validation remains in the Save-to picker / write path.
        places = mount_places()
        if not places:
            return None
        dlg = QFileDialog(parent, caption or "", "", filt or "")
        dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dlg.setFileMode(mode)
        dlg.setAcceptMode(accept)
        if options:
            try:
                for flag in (QFileDialog.Option.ShowDirsOnly, QFileDialog.Option.DontConfirmOverwrite):
                    if options & flag:
                        dlg.setOption(flag, True)
            except Exception:
                pass
        d = str(directory or "")
        if d:
            if os.path.isdir(d):
                dlg.setDirectory(d)
            else:
                dlg.setDirectory(os.path.dirname(d) or ".")
                dlg.selectFile(d)
        if initial_filter:
            dlg.selectNameFilter(str(initial_filter))
        urls = list(dlg.sidebarUrls())
        have = {u.toLocalFile() for u in urls}
        for p in places:      # R32.10.4: mount roots always listed, without synchronous device scans
            if p not in have:
                urls.append(QUrl.fromLocalFile(p)); have.add(p)
        dlg.setSidebarUrls(urls)
        return dlg

    def _args(args, kwargs, names):
        out = dict(zip(names, args))
        out.update(kwargs)
        return out

    def save(*args, **kwargs):
        a = _args(args, kwargs, ("parent", "caption", "directory", "filter", "initialFilter", "options"))
        try:
            dlg = build(a.get("parent"), a.get("caption"), a.get("directory"), a.get("filter"),
                        a.get("initialFilter"), a.get("options"), QFileDialog.FileMode.AnyFile, QFileDialog.AcceptMode.AcceptSave)
            if dlg is None:
                return orig_save(*args, **kwargs)
            if dlg.exec():
                sel = dlg.selectedFiles()
                return (sel[0] if sel else "", dlg.selectedNameFilter())
            return ("", "")
        except Exception:
            return orig_save(*args, **kwargs)

    def open_one(*args, **kwargs):
        a = _args(args, kwargs, ("parent", "caption", "directory", "filter", "initialFilter", "options"))
        try:
            dlg = build(a.get("parent"), a.get("caption"), a.get("directory"), a.get("filter"),
                        a.get("initialFilter"), a.get("options"), QFileDialog.FileMode.ExistingFile, QFileDialog.AcceptMode.AcceptOpen)
            if dlg is None:
                return orig_open(*args, **kwargs)
            if dlg.exec():
                sel = dlg.selectedFiles()
                return (sel[0] if sel else "", dlg.selectedNameFilter())
            return ("", "")
        except Exception:
            return orig_open(*args, **kwargs)

    def open_many(*args, **kwargs):
        a = _args(args, kwargs, ("parent", "caption", "directory", "filter", "initialFilter", "options"))
        try:
            dlg = build(a.get("parent"), a.get("caption"), a.get("directory"), a.get("filter"),
                        a.get("initialFilter"), a.get("options"), QFileDialog.FileMode.ExistingFiles, QFileDialog.AcceptMode.AcceptOpen)
            if dlg is None:
                return orig_many(*args, **kwargs)
            if dlg.exec():
                return (list(dlg.selectedFiles()), dlg.selectedNameFilter())
            return ([], "")
        except Exception:
            return orig_many(*args, **kwargs)

    def pick_dir(*args, **kwargs):
        a = _args(args, kwargs, ("parent", "caption", "directory", "options"))
        try:
            opts = a.get("options")
            if opts is None:
                opts = QFileDialog.Option.ShowDirsOnly
            dlg = build(a.get("parent"), a.get("caption"), a.get("directory"), "", "", opts,
                        QFileDialog.FileMode.Directory, QFileDialog.AcceptMode.AcceptOpen)
            if dlg is None:
                return orig_dir(*args, **kwargs)
            if dlg.exec():
                sel = dlg.selectedFiles()
                return sel[0] if sel else ""
            return ""
        except Exception:
            return orig_dir(*args, **kwargs)

    QFileDialog.getSaveFileName = staticmethod(save)
    QFileDialog.getOpenFileName = staticmethod(open_one)
    QFileDialog.getOpenFileNames = staticmethod(open_many)
    QFileDialog.getExistingDirectory = staticmethod(pick_dir)
    _INSTALLED = True
    return True


# R32.10: why a plugged-in stick is not offered, and a one-click mount for drives nothing mounted.
def drive_problems(mountinfo="/proc/self/mountinfo", sys_block="/sys/block"):
    """Linux: removable disks that are NOT usable as a save target, with the reason.

    [{device, reason, fix}] where reason is "not mounted", "mounted read-only" or "no write permission".
    """
    import sys as _sys
    if not _sys.platform.startswith("linux"):
        return []
    mounts = {}
    try:
        with open(mountinfo, "r", encoding="utf-8", errors="replace") as f:
            for line in f.read().splitlines():
                try:
                    left, right = line.split(" - ", 1)
                    lf = left.split(); mounts.setdefault(right.split()[1], (_unescape(lf[4]), lf[5].split(",")))
                except (ValueError, IndexError):
                    continue
    except OSError:
        return []
    out = []
    try:
        disks = sorted(os.listdir(sys_block))
    except OSError:
        return []
    for disk in disks:
        try:
            with open(os.path.join(sys_block, disk, "removable")) as f:
                rem = f.read().strip() == "1"
        except OSError:
            rem = False
        if not (rem or disk.startswith("mmcblk") or "/usb" in os.path.realpath(os.path.join(sys_block, disk))):
            continue
        if disk.startswith(("loop", "sr", "ram", "zram")):
            continue
        try:
            with open(os.path.join(sys_block, disk, "size")) as f:
                if int(f.read().strip() or 0) == 0:
                    continue                        # empty card reader slot
        except (OSError, ValueError):
            pass
        parts = [p for p in sorted(os.listdir(os.path.join(sys_block, disk))) if p.startswith(disk)] or [disk]
        for part in parts:
            dev = "/dev/" + part
            if dev not in mounts:
                if len(parts) > 1 and part == disk:
                    continue
                out.append({"device": dev, "reason": "not mounted", "fix": "mount"})
                continue
            mnt, opts = mounts[dev]
            if "ro" in opts:
                out.append({"device": dev, "path": mnt, "reason": "mounted read-only",
                            "fix": "The drive is read-only (locked SD switch, or a damaged NTFS/exFAT volume — repair it on another computer)."})
            elif not os.access(mnt, os.W_OK):
                out.append({"device": dev, "path": mnt, "reason": "no write permission",
                            "fix": "Mounted for another user. Re-plug it while logged in, or remount it with your user (udisksctl)."})
    return out


def mount_drive(device):
    """Mount a removable partition for the current user with udisksctl (no root, no partition change)."""
    exe = shutil.which("udisksctl")
    if not exe:
        return False, "udisksctl is not installed — mount the drive with your file manager, or install udisks2."
    try:
        r = subprocess.run([exe, "mount", "-b", str(device), "--no-user-interaction"], capture_output=True, text=True, timeout=30)
    except Exception as exc:
        return False, str(exc)
    msg = (r.stdout or r.stderr or "").strip()
    return r.returncode == 0, msg
