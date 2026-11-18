"""Crash-safe file writers and readers shared by every Groovebox module.

Writers put the data in a temporary file in the same directory, flush and fsync it, keep the previous
version as a hidden ``.<name>.bak`` and then atomically replace the target, so a power cut or crash mid-save
never leaves a truncated settings/project file.  Readers behave exactly like ``json.load(open(p))``
except that a corrupt or empty file falls back to the ``.bak`` copy before raising the original error.
"""
import json
import os
import tempfile
import threading

_LOCKS = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for(path):
    with _LOCKS_GUARD:
        lk = _LOCKS.get(path)
        if lk is None:
            lk = _LOCKS[path] = threading.Lock()
        return lk


def backup_path(path):
    """Hidden previous-version copy next to the file: <dir>/.<name>.bak"""
    path = os.fspath(path)
    return os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".bak")


def _fspath(path):
    return os.path.abspath(os.fspath(path))


def atomic_write_bytes(path, data, backup=True):
    path = _fspath(path)
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    with _lock_for(path):
        fd, tmp = tempfile.mkstemp(prefix="." + os.path.basename(path) + ".", suffix=".tmp", dir=d)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass
            try:
                if os.path.exists(path):
                    os.chmod(tmp, os.stat(path).st_mode & 0o7777)
            except OSError:
                pass
            if backup and os.path.isfile(path) and os.path.getsize(path) > 0:
                try:
                    bak = backup_path(path)
                    if os.path.exists(bak):
                        os.remove(bak)
                    os.link(path, bak)
                except OSError:
                    pass
            os.replace(tmp, path)
            try:
                dfd = os.open(d, os.O_RDONLY)
                try:
                    os.fsync(dfd)
                finally:
                    os.close(dfd)
            except OSError:
                pass
        except BaseException as exc:
            try:
                os.remove(tmp)
            except OSError:
                pass
            friendly = _friendly_os_error(exc, path)
            if friendly is not None:
                raise friendly from exc
            raise
    return path


def _friendly_os_error(exc, path):
    """Disk full / read-only / quota errors get one clear sentence (same errno, so callers still match)."""
    import errno as _e
    if not isinstance(exc, OSError) or isinstance(exc, SystemFileProtected if "SystemFileProtected" in globals() else ()):
        return None
    msgs = {getattr(_e, "ENOSPC", -1): "the drive is full",
            getattr(_e, "EDQUOT", -2): "the storage quota is used up",
            getattr(_e, "EROFS", -3): "the drive is read-only (write-protect switch or a system folder)"}
    m = msgs.get(exc.errno)
    if not m:
        return None
    err = OSError(exc.errno, "Could not save %s: %s" % (os.path.basename(path), m))
    err.filename = path
    _notify_save_problem(err)
    return err


def _notify_save_problem(err):
    try:
        import notify_center
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        host = getattr(app, "_groovebox_main", None) if app is not None else None
        if host is None and app is not None:
            for w in app.topLevelWidgets():
                if hasattr(w, "_notify_state"):
                    host = w; break
        if host is not None:
            notify_center.notify(host, str(err.strerror), "warn", key="save-" + str(err.errno), every_s=20.0)
    except Exception:
        pass


def estimate_export_bytes(kind, options):
    """Rough upper estimate of an export's size from its options (seconds, sample rate, resolution, bitrate)."""
    o = options if isinstance(options, dict) else {}
    def num(*keys, default=0.0):
        for k in keys:
            try:
                v = float(o.get(k))
                if v > 0:
                    return v
            except Exception:
                pass
        return default
    secs = num("duration_s", "duration", "seconds", "length_s", "total_seconds", default=0.0)
    if secs <= 0:
        return 0
    if "audio" in str(kind):
        sr = num("sample_rate", "sr", "rate", default=48000.0); ch = num("channels", default=2.0)
        bits = num("bit_depth", "bits", default=32.0)
        return int(secs * sr * ch * bits / 8 * 1.1)
    w = num("width", default=1920.0); h = num("height", default=1080.0); fps = num("fps", default=30.0)
    br = num("video_bitrate", "bitrate", default=0.0)
    if br <= 0:
        br = w * h * fps * 0.15            # bits/s, generous for H.264 at high quality
    elif br < 100000:
        br *= 1000.0                       # given in kbit/s
    return int(secs * (br + 320000) / 8 * 1.25)


def atomic_write_text(path, text, encoding="utf-8", backup=True):
    return atomic_write_bytes(path, str(text).encode(encoding), backup=backup)


def atomic_write_json(path, obj, encoding="utf-8", backup=True, **kw):
    """Same keyword arguments as json.dump (indent, sort_keys, default, ensure_ascii, ...)."""
    text = json.dumps(obj, **kw)
    return atomic_write_text(path, text, encoding=encoding, backup=backup)


def load_json(path, encoding="utf-8", **kw):
    """json.load(open(path)) with .bak recovery for corrupt/empty files; missing files still raise."""
    path = os.fspath(path)
    try:
        with open(path, "r", encoding=encoding) as f:
            return json.load(f, **kw)
    except (ValueError, UnicodeDecodeError) as first:
        for bak in (backup_path(path), path + ".bak"):
          try:
            with open(bak, "r", encoding=encoding) as f:
                return json.load(f, **kw)
          except Exception:
            pass
        raise first


def read_json(path, default=None, **kw):
    """Never raises: returns ``default`` when the file is missing or unrecoverable."""
    try:
        return load_json(path, **kw)
    except Exception:
        return default


# ---------------------------------------------------------------- system-file protection (R101)
# The user may browse and view system files, but nothing in Groovebox may edit, save over, delete,
# rename, move, copy or paste them (as source or destination).  The deepest matching root decides,
# so the Groovebox data folder, home, temp and removable media stay fully usable even when they sit
# under a protected tree.

class SystemFileProtected(PermissionError):
    pass


def _norm(p):
    try:
        return os.path.normcase(os.path.realpath(os.path.abspath(os.path.expanduser(os.fspath(p)))))
    except Exception:
        return os.path.normcase(os.path.abspath(os.fspath(p)))


def _system_roots():
    roots = []
    if os.name == "nt":
        for var in ("SystemRoot", "windir", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "ProgramData"):
            v = os.environ.get(var)
            if v:
                roots.append(v)
        sd = os.environ.get("SystemDrive", "C:")
        roots += [sd + "\\$Recycle.Bin", sd + "\\Recovery", sd + "\\System Volume Information", sd + "\\Boot"]
    else:
        roots += ["/etc", "/usr", "/bin", "/sbin", "/lib", "/lib32", "/lib64", "/libx32", "/boot", "/efi",
                  "/opt", "/var", "/proc", "/sys", "/dev", "/run", "/root", "/srv", "/snap", "/lost+found",
                  "/System", "/Library", "/Applications", "/private", "/cores", "/nix"]
        home = os.path.expanduser("~")
        for rel in (".ssh", ".gnupg", ".bashrc", ".profile", ".bash_profile", ".zshrc", ".xinitrc",
                    ".config/autostart", ".config/labwc", ".config/systemd", ".local/share/applications"):
            roots.append(os.path.join(home, rel))
    # Groovebox's own installed program files.
    roots.append(os.path.dirname(os.path.abspath(__file__)))
    return roots


def _user_roots():
    roots = [os.path.expanduser("~"), tempfile.gettempdir()]
    if os.name != "nt":
        roots += ["/home", "/tmp", "/var/tmp", "/media", "/mnt", "/run/media", "/Volumes", "/var/lib/groovebox",
                  "/private/tmp", "/private/var/folders", "/Users"]
    for env in ("GROOVEBOX_DATA_DIR", "XDG_MUSIC_DIR", "XDG_VIDEOS_DIR"):
        v = os.environ.get(env, "").strip()
        if v:
            roots.append(v)
    try:
        import groovebox_paths
        roots.append(groovebox_paths.base_dir())
    except Exception:
        pass
    return roots


def _inside(path, root):
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def is_system_path(path):
    """True when ``path`` is an OS / program file the user may view but not change."""
    if not path:
        return False
    p = _norm(path)
    if os.name != "nt" and p == "/":
        return True
    best_len, best_sys = -1, False
    for r in _system_roots():
        r = _norm(r)
        if _inside(p, r) and len(r) > best_len:
            best_len, best_sys = len(r), True
    for r in _user_roots():
        r = _norm(r)
        if _inside(p, r) and len(r) >= best_len:
            best_len, best_sys = len(r), False
    if best_len < 0:
        # Unknown top-level location (e.g. /data, D:\\): user space unless it is the drive root itself.
        return os.path.dirname(p) == p
    return best_sys


def protected_message(path, action="change"):
    return ("%s is a system file. Groovebox lets you view system files but never %s them "
            "(no edit, delete, rename, move, copy or paste)." % (path, action))


def guard_user_paths(*paths, action="change"):
    """Raise SystemFileProtected if any path (source or destination) is a system file."""
    for p in paths:
        if p and is_system_path(p):
            raise SystemFileProtected(protected_message(p, action))
    return True


def install_qt_save_guard():
    """Make every QFileDialog save prompt refuse system locations (called once at startup)."""
    try:
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
    except Exception:
        return False
    if getattr(QFileDialog, "_gb_system_guard", False):
        return True
    orig = QFileDialog.getSaveFileName

    def guarded(*a, **kw):
        res = orig(*a, **kw)
        path = res[0] if isinstance(res, tuple) else res
        if path and is_system_path(path):
            try:
                parent = a[0] if a else kw.get("parent")
                QMessageBox.warning(parent, "System file protected", protected_message(path, "save over"))
            except Exception:
                pass
            return ("", "") if isinstance(res, tuple) else ""
        return res

    QFileDialog.getSaveFileName = staticmethod(guarded)
    QFileDialog._gb_system_guard = True
    return True
